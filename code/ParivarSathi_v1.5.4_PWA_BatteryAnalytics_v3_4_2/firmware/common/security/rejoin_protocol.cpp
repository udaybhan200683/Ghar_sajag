#include "firmware/common/security/rejoin_protocol.hpp"

namespace gs::security {
namespace {
void append(Bytes& out, const std::uint8_t* bytes, std::size_t size) {
    out.insert(out.end(), bytes, bytes + size);
}

void append_string(Bytes& out, const std::string& value) {
    out.push_back(static_cast<std::uint8_t>(value.size()));
    out.insert(out.end(), value.begin(), value.end());
}

void append_u64(Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}

Bytes hello_bytes(const RejoinHello& hello) {
    Bytes out{'G', 'S', '-', 'P', '2', '-', 'R', 'E', 'J', 'O', 'I', 'N', '-', 'v', '1', 0};
    out.push_back(hello.version);
    append_string(out, hello.device_id);
    append_string(out, hello.hub_id);
    append_string(out, hello.home_id);
    append_string(out, hello.logical_id);
    append_u64(out, hello.session);
    append(out, hello.node_challenge.data(), hello.node_challenge.size());
    return out;
}

Bytes challenge_bytes(const RejoinHello& hello, const RejoinChallenge& challenge) {
    Bytes out = hello_bytes(hello);
    append(out, hello.authentication.data(), hello.authentication.size());
    append(out, challenge.hub_challenge.data(), challenge.hub_challenge.size());
    return out;
}

Bytes tagged(const Bytes& transcript, const char* label) {
    Bytes out;
    while (*label) out.push_back(static_cast<std::uint8_t>(*label++));
    out.push_back(0);
    append(out, transcript.data(), transcript.size());
    return out;
}

bool mac(CommissioningCrypto& crypto, const Key32& key, const Bytes& transcript,
         const char* label, Key32& out) {
    return crypto.hmac_sha256(key, tagged(transcript, label), out);
}

bool equal(CommissioningCrypto& crypto, const Key32& left, const Key32& right) {
    return crypto.constant_time_equal(left.data(), right.data(), left.size());
}

bool derive_salt(CommissioningCrypto& crypto, const CommissioningBinding& binding,
                 const RejoinHello& hello, const RejoinChallenge& challenge,
                 Key32& out) {
    Bytes nonce_salt;
    append(nonce_salt, hello.node_challenge.data(), hello.node_challenge.size());
    append(nonce_salt, challenge.hub_challenge.data(), challenge.hub_challenge.size());
    return crypto.hkdf_sha256(binding.installation_key, nonce_salt,
                               tagged(challenge_bytes(hello, challenge),
                                      "GS-P2-REJOIN-SESSION-SALT-v1"), out);
}
}  // namespace

HubRejoin::HubRejoin(CommissioningCrypto& crypto, const CommissioningBinding& binding,
                     std::uint64_t last_accepted_session)
    : crypto_(crypto), binding_(binding), last_session_(last_accepted_session) {}

HubRejoin::~HubRejoin() {
    if (session_salt_) crypto_.secure_zero(session_salt_->data(), session_salt_->size());
}

std::optional<RejoinChallenge> HubRejoin::accept(const RejoinHello& hello) {
    if (state_ != State::Idle || hello.version != 1 || hello.session == 0 ||
        hello.session <= last_session_ || hello.device_id != binding_.device_id ||
        hello.hub_id != binding_.hub_id || hello.home_id != binding_.home_id ||
        hello.logical_id != binding_.logical_id) return std::nullopt;
    Key32 expected{};
    const bool authenticated = mac(crypto_, binding_.installation_key,
                                    hello_bytes(hello), "GS-P2-REJOIN-HELLO-v1", expected) &&
                               equal(crypto_, expected, hello.authentication);
    crypto_.secure_zero(expected.data(), expected.size());
    if (!authenticated) return std::nullopt;
    if (!crypto_.random_bytes(challenge_.hub_challenge.data(),
                               challenge_.hub_challenge.size())) return std::nullopt;
    hello_ = hello;
    if (!mac(crypto_, binding_.installation_key, challenge_bytes(hello_, challenge_),
             "GS-P2-REJOIN-HUB-v1", challenge_.authentication)) return std::nullopt;
    state_ = State::Challenged;
    return challenge_;
}

std::optional<RejoinAck> HubRejoin::confirm(const RejoinFinal& final) {
    if (state_ != State::Challenged && state_ != State::Confirmed) return std::nullopt;
    const auto transcript = challenge_bytes(hello_, challenge_);
    Key32 expected{};
    const bool authenticated = mac(crypto_, binding_.installation_key,
                                    transcript, "GS-P2-REJOIN-NODE-FINAL-v1", expected) &&
                               equal(crypto_, expected, final.confirmation);
    crypto_.secure_zero(expected.data(), expected.size());
    if (!authenticated) return std::nullopt;
    RejoinAck ack;
    if (!mac(crypto_, binding_.installation_key, transcript,
             "GS-P2-REJOIN-HUB-ACK-v1", ack.confirmation)) return std::nullopt;
    if (!session_salt_) {
        Key32 salt{};
        if (!derive_salt(crypto_, binding_, hello_, challenge_, salt)) return std::nullopt;
        session_salt_ = salt;
        crypto_.secure_zero(salt.data(), salt.size());
    }
    accepted_session_ = hello_.session;
    state_ = State::Confirmed;
    return ack;
}

NodeRejoin::NodeRejoin(CommissioningCrypto& crypto, const CommissioningBinding& binding,
                       std::uint64_t next_session)
    : crypto_(crypto), binding_(binding), next_session_(next_session) {}

NodeRejoin::~NodeRejoin() {
    if (session_salt_) crypto_.secure_zero(session_salt_->data(), session_salt_->size());
}

std::optional<RejoinHello> NodeRejoin::begin() {
    if (state_ != State::Idle || next_session_ == 0) return std::nullopt;
    hello_.device_id = binding_.device_id;
    hello_.hub_id = binding_.hub_id;
    hello_.home_id = binding_.home_id;
    hello_.logical_id = binding_.logical_id;
    hello_.session = next_session_;
    if (!crypto_.random_bytes(hello_.node_challenge.data(),
                               hello_.node_challenge.size()) ||
        !mac(crypto_, binding_.installation_key, hello_bytes(hello_),
             "GS-P2-REJOIN-HELLO-v1", hello_.authentication)) return std::nullopt;
    state_ = State::HelloSent;
    return hello_;
}

std::optional<RejoinFinal> NodeRejoin::accept(const RejoinChallenge& challenge) {
    if (state_ != State::HelloSent) return std::nullopt;
    const auto transcript = challenge_bytes(hello_, challenge);
    Key32 expected{};
    const bool authenticated = mac(crypto_, binding_.installation_key,
                                    transcript, "GS-P2-REJOIN-HUB-v1", expected) &&
                               equal(crypto_, expected, challenge.authentication);
    crypto_.secure_zero(expected.data(), expected.size());
    if (!authenticated) return std::nullopt;
    challenge_ = challenge;
    RejoinFinal final;
    if (!mac(crypto_, binding_.installation_key, transcript,
             "GS-P2-REJOIN-NODE-FINAL-v1", final.confirmation)) return std::nullopt;
    state_ = State::FinalSent;
    return final;
}

bool NodeRejoin::commit(const RejoinAck& ack) {
    if (state_ != State::FinalSent && state_ != State::Committed) return false;
    const auto transcript = challenge_bytes(hello_, challenge_);
    Key32 expected{};
    const bool authenticated = mac(crypto_, binding_.installation_key,
                                    transcript, "GS-P2-REJOIN-HUB-ACK-v1", expected) &&
                               equal(crypto_, expected, ack.confirmation);
    crypto_.secure_zero(expected.data(), expected.size());
    if (!authenticated) return false;
    if (!session_salt_) {
        Key32 salt{};
        if (!derive_salt(crypto_, binding_, hello_, challenge_, salt)) return false;
        session_salt_ = salt;
        crypto_.secure_zero(salt.data(), salt.size());
    }
    state_ = State::Committed;
    return true;
}

}  // namespace gs::security
