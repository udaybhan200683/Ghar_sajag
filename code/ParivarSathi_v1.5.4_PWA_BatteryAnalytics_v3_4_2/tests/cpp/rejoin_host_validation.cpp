#include "firmware/common/security/rejoin_protocol.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

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
        std::cout << "P2-REJOIN-HOST PASS mutual proof/session/Home/replay\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-REJOIN-HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
