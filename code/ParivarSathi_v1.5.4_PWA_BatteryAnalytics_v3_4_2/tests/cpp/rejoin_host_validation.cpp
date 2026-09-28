#include "firmware/common/security/rejoin_protocol.hpp"
#include "firmware/common/security/commissioning_wire.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/node/components/power/session_recovery_policy.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>
#include <vector>

using namespace gs::security;
using gs::host::security::OpenSslCommissioningCrypto;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        CommissioningBinding binding;
        binding.device_id = "device-a";
        binding.hub_id = "hub-a";
        binding.home_id = "home-a";
        binding.logical_id = "bathroom";
        require(crypto.random_bytes(binding.installation_key.data(),
                                    binding.installation_key.size()), "test key RNG failed");
        NodeRejoin node(crypto, binding, 2);
        HubRejoin hub(crypto, binding, 1);
        const auto hello = node.begin();
        require(hello.has_value(), "Node did not open rejoin");
        auto altered_hello = *hello;
        altered_hello.logical_id = "kitchen";
        require(!hub.accept(altered_hello), "Hub accepted altered logical ID");
        auto challenge = hub.accept(*hello);
        require(challenge.has_value(), "Hub rejected authenticated rejoin");
        const auto repeated_challenge = hub.accept(*hello);
        require(repeated_challenge.has_value() &&
                repeated_challenge->hub_challenge == challenge->hub_challenge &&
                repeated_challenge->authentication == challenge->authentication,
                "retransmitted Hello changed the pending challenge");
        auto altered_challenge = *challenge;
        altered_challenge.hub_challenge[0] ^= 1;
        require(!node.accept(altered_challenge), "Node accepted altered Hub challenge");
        auto final = node.accept(*challenge);
        require(final.has_value(), "Node rejected bound Hub challenge");
        auto altered_final = *final;
        altered_final.confirmation[0] ^= 1;
        require(!hub.confirm(altered_final), "Hub accepted forged Node confirmation");
        auto ack = hub.confirm(*final);
        require(ack.has_value() && hub.authenticated_session() == 2 &&
                hub.session_salt().has_value(), "Hub did not authenticate session");
        auto altered_ack = *ack;
        altered_ack.confirmation[0] ^= 1;
        require(!node.commit(altered_ack) && !node.session_salt(),
                "Node accepted forged final ACK");
        require(node.commit(*ack) && node.session_salt() == hub.session_salt(),
                "rejoin session salt disagreed");
        require(!hub.accept(*hello), "committed equal-session Hello replayed");
        require(!node.begin(), "committed Node restarted pairing without a fresh session");

        HubRejoin stale(crypto, binding, 2);
        require(!stale.accept(*hello), "Hub accepted old session replay");
        auto foreign_binding = binding;
        foreign_binding.home_id = "other-home";
        HubRejoin foreign(crypto, foreign_binding, 1);
        require(!foreign.accept(*hello), "foreign Home accepted rejoin");
        auto wrong_key = binding;
        wrong_key.installation_key[0] ^= 1;
        HubRejoin copied_identity(crypto, wrong_key, 1);
        require(!copied_identity.accept(*hello), "copied public identity bypassed key proof");

        NodeRejoin new_node(crypto, binding, 3, 2);
        HubRejoin new_hub(crypto, binding, 2);
        const auto v2_hello = new_node.begin();
        require(v2_hello.has_value() &&
                v2_hello->offered_capabilities == kHealthAckCapability,
                "v2 capability offer missing");
        wire::Message v1_wire, v2_wire;
        require(wire::encode(*hello, v1_wire) && wire::encode(*v2_hello, v2_wire) &&
                v2_wire.body.size() == v1_wire.body.size() + 4,
                "v2 body did not use a distinct capability encoding");
        RejoinHello decoded_v2;
        require(wire::decode(v2_wire, decoded_v2) &&
                decoded_v2.offered_capabilities == kHealthAckCapability,
                "v2 offer wire round trip failed");
        auto maximum_binding = binding;
        maximum_binding.device_id = "c3-001122334455";
        maximum_binding.hub_id = "hub-001122334455";
        maximum_binding.home_id = std::string(64, 'h');
        maximum_binding.logical_id = std::string(64, 'l');
        NodeRejoin maximum_node(crypto, maximum_binding, 6, 2);
        wire::Message maximum_wire;
        std::vector<wire::Packet> maximum_packets;
        const auto maximum_hello = maximum_node.begin();
        require(maximum_hello.has_value() && wire::encode(*maximum_hello, maximum_wire) &&
                wire::fragment(maximum_wire, 1, maximum_packets) &&
                maximum_packets.size() == 1,
                "target v2 Hello does not fit a nonblocking ESP-NOW packet");
        auto altered_offer = *v2_hello;
        altered_offer.offered_capabilities = 0;
        require(!new_hub.accept(altered_offer), "tampered v2 offer authenticated");
        auto altered_version = *v2_hello;
        altered_version.version = 1;
        altered_version.offered_capabilities = 0;
        require(!new_hub.accept(altered_version), "v2 proof accepted as v1");
        const auto v2_challenge = new_hub.accept(*v2_hello);
        require(v2_challenge.has_value() && v2_challenge->version == 2 &&
                v2_challenge->selected_capabilities == kHealthAckCapability,
                "v2 capability not selected");
        wire::Message challenge_wire;
        RejoinChallenge decoded_challenge;
        require(wire::encode(*v2_challenge, challenge_wire) &&
                wire::decode(challenge_wire, decoded_challenge) &&
                decoded_challenge.selected_capabilities == kHealthAckCapability,
                "v2 selected capability wire round trip failed");
        auto altered_selection = *v2_challenge;
        altered_selection.selected_capabilities = 0;
        require(!new_node.accept(altered_selection), "tampered selection authenticated");
        const auto v2_final = new_node.accept(*v2_challenge);
        require(v2_final.has_value(), "v2 challenge rejected");
        const auto v2_ack = new_hub.confirm(*v2_final);
        require(v2_ack.has_value() && new_node.commit(*v2_ack) &&
                new_node.session_salt() == new_hub.session_salt(),
                "v2 completion failed");
        NodeRejoin no_offer_node(crypto, binding, 5, 2, 0);
        HubRejoin no_offer_hub(crypto, binding, 4);
        const auto no_offer_hello = no_offer_node.begin();
        const auto no_offer_challenge = no_offer_hello
            ? no_offer_hub.accept(*no_offer_hello) : std::nullopt;
        require(no_offer_challenge.has_value() &&
                no_offer_challenge->selected_capabilities == 0,
                "Hub selected an unoffered capability");
        auto unoffered_selection = *no_offer_challenge;
        unoffered_selection.selected_capabilities = kHealthAckCapability;
        require(!no_offer_node.accept(unoffered_selection),
                "Node accepted an unoffered selection");
        HubRejoin equal_floor(crypto, binding, 3);
        require(!equal_floor.accept(*v2_hello), "equal floor accepted");

        NodeRejoin candidate_c(crypto, binding, 4, 2);
        HubRejoin rebooted_hub(crypto, binding, 3);
        const auto c_hello = candidate_c.begin();
        const auto c_challenge = c_hello ? rebooted_hub.accept(*c_hello)
                                         : std::nullopt;
        require(c_hello.has_value() && c_challenge.has_value(),
                "C did not advance after ambiguous B commit");
        const auto c_final = candidate_c.accept(*c_challenge);
        require(c_final.has_value(), "C final failed");
        const auto c_ack = rebooted_hub.confirm(*c_final);
        require(c_ack.has_value() && !candidate_c.commit(*v2_ack) &&
                candidate_c.commit(*c_ack), "old B ACK completed C");

        NodeRejoin ambiguous_b(crypto, binding, 7, 2);
        HubRejoin before_reboot(crypto, binding, 6);
        const auto b_hello = ambiguous_b.begin();
        const auto b_challenge = b_hello ? before_reboot.accept(*b_hello)
                                         : std::nullopt;
        const auto b_final = b_challenge ? ambiguous_b.accept(*b_challenge)
                                         : std::nullopt;
        const auto lost_b_ack = b_final ? before_reboot.confirm(*b_final)
                                        : std::nullopt;
        require(lost_b_ack.has_value(), "ambiguous B did not commit at Hub");
        HubRejoin after_reboot(crypto, binding, 7);
        require(!after_reboot.accept(*b_hello),
                "rebooted Hub accepted equal committed B");
        NodeRejoin advanced_c(crypto, binding, 8, 2);
        const auto advanced_hello = advanced_c.begin();
        const auto advanced_challenge = advanced_hello
            ? after_reboot.accept(*advanced_hello) : std::nullopt;
        const auto advanced_final = advanced_challenge
            ? advanced_c.accept(*advanced_challenge) : std::nullopt;
        const auto advanced_ack = advanced_final
            ? after_reboot.confirm(*advanced_final) : std::nullopt;
        require(advanced_ack.has_value() && !advanced_c.commit(*lost_b_ack) &&
                advanced_c.commit(*advanced_ack),
                "C failed to resolve committed B with lost ACK and Hub reboot");

        RuntimeFrameSecurity old_sender(crypto, binding);
        RuntimeFrameSecurity new_receiver(crypto, binding);
        RuntimeFrameSecurity old_receiver(crypto, binding);
        require(old_sender.start(3, *new_node.session_salt()) &&
                old_receiver.start(3, *new_node.session_salt()) &&
                new_receiver.start(4, *candidate_c.session_salt()),
                "secure frame session setup failed");
        const auto health_ack = gs::transport::encode_node_health_ack(9);
        require(static_cast<bool>(health_ack), "health ACK encoding failed");
        SecureFrame protected_health_ack;
        gs::transport::EncodedFrame opened;
        require(old_sender.seal(RuntimeDirection::Downlink, health_ack.frame,
                                protected_health_ack) &&
                old_receiver.open(RuntimeDirection::Downlink, protected_health_ack,
                                  opened) &&
                !old_receiver.open(RuntimeDirection::Downlink, protected_health_ack,
                                   opened) &&
                !new_receiver.open(RuntimeDirection::Downlink, protected_health_ack,
                                   opened), "duplicate or old-session health ACK accepted");
        const auto decoded_health_ack = gs::transport::decode_node_health_ack(
            health_ack.frame.bytes.data(), health_ack.frame.size);
        require(decoded_health_ack && *decoded_health_ack.value == 9,
                "health ACK codec round trip failed");

        using gs::node::SessionRecoveryPolicy;
        require(SessionRecoveryPolicy::health_ack_matches(true, 9, 9) &&
                !SessionRecoveryPolicy::health_ack_matches(true, 9, 8) &&
                !SessionRecoveryPolicy::health_ack_matches(true, std::nullopt, 9) &&
                !SessionRecoveryPolicy::health_ack_matches(false, 9, 9),
                "unmatched, stale, or legacy health ACK refreshed contact");
        require(!SessionRecoveryPolicy::idle_expired(true, 429999, 0) &&
                SessionRecoveryPolicy::idle_expired(true, 430000, 0) &&
                !SessionRecoveryPolicy::idle_expired(false, 900000, 0),
                "quiet contact timeout or v1 compatibility failed");
        require(!SessionRecoveryPolicy::idle_expired(true, 360000, 0) &&
                !SessionRecoveryPolicy::idle_expired(true, 360000, 240000) &&
                !SessionRecoveryPolicy::idle_expired(true, 400000, 360000),
                "lost ACK or temporary RF outage caused churn");
        require(!SessionRecoveryPolicy::active_expired(true, 10000, 0, 2, 0) &&
                !SessionRecoveryPolicy::active_expired(true, 9999, 0, 3, 0) &&
                SessionRecoveryPolicy::active_expired(true, 10000, 0, 3, 0) &&
                !SessionRecoveryPolicy::active_expired(true, 10000, 0, 3, 5000),
                "active event trigger boundaries failed");
        require(SessionRecoveryPolicy::may_fallback(false, false, 2, 30000) &&
                !SessionRecoveryPolicy::may_fallback(true, false, 2, 30000) &&
                !SessionRecoveryPolicy::may_fallback(false, true, 2, 30000) &&
                !SessionRecoveryPolicy::may_fallback(false, false, 2, 29999),
                "v2 downgrade policy failed");
        require(!SessionRecoveryPolicy::ambiguity_expired(180000, -1, 8, 180000) &&
                !SessionRecoveryPolicy::ambiguity_expired(179999, 0, 4, 180000) &&
                !SessionRecoveryPolicy::ambiguity_expired(180000, 0, 3, 180000) &&
                SessionRecoveryPolicy::ambiguity_expired(180000, 0, 4, 180000) &&
                SessionRecoveryPolicy::next_ambiguity_window(1800000) == 3600000 &&
                SessionRecoveryPolicy::next_ambiguity_window(3600000) == 3600000 &&
                SessionRecoveryPolicy::retry_delay(10, 4) < 60101,
                "ambiguity window or bounded backoff failed");
        std::int64_t ambiguity_window =
            SessionRecoveryPolicy::initial_ambiguity_window_ms;
        for (unsigned candidate = 0; candidate < 8; ++candidate)
            ambiguity_window = SessionRecoveryPolicy::next_ambiguity_window(
                ambiguity_window);
        require(ambiguity_window == SessionRecoveryPolicy::maximum_ambiguity_window_ms &&
                !SessionRecoveryPolicy::ambiguity_expired(86400000, -1, 100, ambiguity_window),
                "prolonged no-challenge outage advanced session candidates");
        std::cout << "P2-REJOIN-HOST PASS mutual proof/session/Home/replay\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-REJOIN-HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
