#include "host/security/openssl_commissioning_crypto.hpp"
#include "firmware/common/security/commissioning_protocol.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>

using gs::host::security::OpenSslCommissioningCrypto;
using namespace gs::security;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        require(crypto.generate_test_identity("node-a") && crypto.generate_test_identity("hub-a") &&
                !crypto.generate_test_identity("node-a"), "test-only key generation failed");
        P256PublicKey node_public{}, hub_public{};
        require(crypto.identity_public_key("node-a", node_public) &&
                crypto.identity_public_key("hub-a", hub_public) && node_public != hub_public,
                "unique identity public keys missing");
        Bytes transcript{'G', 'S', '-', 'P', '2', '-', 'N', 'O', 'D', 'E'};
        P256Signature signature{};
        require(crypto.sign_identity("node-a", transcript, signature) &&
                crypto.verify_identity(node_public, transcript, signature),
                "P-256 identity proof failed");
        require(!crypto.verify_identity(hub_public, transcript, signature),
                "wrong identity verified a Node signature");
        transcript[0] ^= 1;
        require(!crypto.verify_identity(node_public, transcript, signature),
                "modified transcript verified");

        EphemeralP256 node_eph{}, hub_eph{};
        Key32 node_shared{}, hub_shared{}, node_key{}, hub_key{};
        require(crypto.generate_ephemeral(node_eph) && crypto.generate_ephemeral(hub_eph) &&
                crypto.derive_shared(node_eph, hub_eph.public_key, node_shared) &&
                crypto.derive_shared(hub_eph, node_eph.public_key, hub_shared) &&
                node_shared == hub_shared, "ephemeral ECDH was not mutual");
        Bytes salt(32), context{'G', 'S', '-', 'P', '2', '-', 'H', 'O', 'M', 'E'};
        require(crypto.random_bytes(salt.data(), salt.size()) &&
                crypto.hkdf_sha256(node_shared, salt, context, node_key) &&
                crypto.hkdf_sha256(hub_shared, salt, context, hub_key) &&
                node_key == hub_key, "HKDF session keys differed");
        Key32 mac{};
        require(crypto.hmac_sha256(node_key, context, mac) &&
                std::any_of(mac.begin(), mac.end(), [](std::uint8_t value) { return value != 0; }),
                "HMAC confirmation failed");

        Nonce12 nonce{};
        require(crypto.random_bytes(nonce.data(), nonce.size()), "nonce RNG failed");
        Bytes aad{'d', 'a', 't', 'a', '-', 'n', 'o', 'd', 'e', '-', '1'};
        Bytes plain{'m', 'o', 't', 'i', 'o', 'n'}, cipher, opened;
        GcmTag tag{};
        require(crypto.seal_aes256_gcm(node_key, nonce, aad, plain, cipher, tag) &&
                crypto.open_aes256_gcm(hub_key, nonce, aad, cipher, tag, opened) &&
                opened == plain, "AEAD round trip failed");
        aad[0] ^= 1;
        require(!crypto.open_aes256_gcm(hub_key, nonce, aad, cipher, tag, opened) && opened.empty(),
                "modified authenticated metadata was accepted");
        aad[0] ^= 1;
        cipher[0] ^= 1;
        require(!crypto.open_aes256_gcm(hub_key, nonce, aad, cipher, tag, opened) && opened.empty(),
                "modified ciphertext was accepted");
        Bytes empty_plain, empty_cipher, empty_opened;
        GcmTag empty_tag{};
        require(crypto.seal_aes256_gcm(node_key, nonce, aad, empty_plain,
                                       empty_cipher, empty_tag) && empty_cipher.empty() &&
                crypto.open_aes256_gcm(hub_key, nonce, aad, empty_cipher,
                                       empty_tag, empty_opened) && empty_opened.empty(),
                "empty authenticated payload inherited AAD length");

        Key32 installation_code{};
        require(crypto.random_bytes(installation_code.data(), installation_code.size()),
                "installation authorization RNG failed");
        HubCommissioning hub(crypto, "hub-a", "hub-id", "home-id", "node-id",
                             node_public, installation_code, "logical-bathroom",
                             "Bathroom", "motion");
        NodeCommissioning node(crypto, "node-a", "node-id", installation_code);
        require(node.enable_window(100, 5000), "Node pairing intent missing");
        auto offer = hub.open(100, 5000);
        require(offer.has_value(), "bounded Hub offer failed");
        auto node_proof = node.respond(*offer, 101);
        require(node_proof.has_value(), "Node rejected exact authorized Hub offer");
        auto hub_proof = hub.accept(*node_proof, 102);
        require(hub_proof.has_value(), "Hub rejected QR-pinned Node identity");
        auto tampered_hub_proof = *hub_proof;
        tampered_hub_proof.hub_signature[0] ^= 1;
        require(!node.finish(tampered_hub_proof, 103), "forged Hub signature accepted");
        auto final = node.finish(*hub_proof, 103);
        require(final.has_value(), "Node failed to authenticate intended Hub");
        auto ack = hub.confirm(*final, 104);
        require(ack.has_value() && hub.binding().has_value() && !node.binding().has_value(),
                "two-phase association state was not bounded");
        require(node.commit(*ack, 105) && node.binding().has_value(),
                "Node failed to confirm association");
        require(node.binding()->installation_key == hub.binding()->installation_key &&
                node.binding()->home_id == "home-id" && node.binding()->hub_id == "hub-id" &&
                node.binding()->logical_id == "logical-bathroom" &&
                node.binding()->room == "Bathroom" && node.binding()->function == "motion" &&
                node.binding()->device_public_key == node_public &&
                node.binding()->hub_public_key == hub_public,
                "Home/Hub binding or key agreement differed");
        require(!node.respond(*offer, 106), "committed Node accepted replayed offer");
        require(!hub.accept(*node_proof, 106), "committed Hub accepted replayed proof");

        Key32 runtime_salt{};
        require(crypto.random_bytes(runtime_salt.data(), runtime_salt.size()),
                "authenticated runtime salt setup failed");
        RuntimeFrameSecurity secure_node(crypto, *node.binding());
        RuntimeFrameSecurity secure_hub(crypto, *hub.binding());
        require(secure_node.start(1, runtime_salt) && secure_hub.start(1, runtime_salt) &&
                !secure_node.start(1, runtime_salt),
                "runtime session did not enforce forward progression");
        gs::transport::EncodedFrame runtime_plain{};
        runtime_plain.bytes[0] = 0x47;
        runtime_plain.bytes[1] = 0x53;
        runtime_plain.size = 2;
        SecureFrame protected_uplink{};
        gs::transport::EncodedFrame opened_frame{};
        require(secure_node.seal(RuntimeDirection::Uplink, runtime_plain, protected_uplink) &&
                protected_uplink.size == runtime_plain.size + kSecureFrameOverhead &&
                secure_hub.open(RuntimeDirection::Uplink, protected_uplink, opened_frame) &&
                opened_frame.size == runtime_plain.size &&
                opened_frame.bytes[0] == runtime_plain.bytes[0],
                "runtime AEAD uplink did not round trip");
        require(!secure_hub.open(RuntimeDirection::Uplink, protected_uplink, opened_frame) &&
                opened_frame.size == 0, "runtime replay was accepted");
        require(secure_node.seal(RuntimeDirection::Uplink, runtime_plain, protected_uplink),
                "second runtime packet could not be sealed");
        auto changed_uplink = protected_uplink;
        changed_uplink.bytes[12] ^= 1;
        require(!secure_hub.open(RuntimeDirection::Uplink, changed_uplink, opened_frame) &&
                secure_hub.open(RuntimeDirection::Uplink, protected_uplink, opened_frame),
                "runtime tamper was accepted or advanced replay state");
        auto changed_binding = *hub.binding();
        changed_binding.logical_id = "different-logical-node";
        RuntimeFrameSecurity wrong_association(crypto, changed_binding);
        require(wrong_association.start(1, runtime_salt) &&
                !wrong_association.open(RuntimeDirection::Uplink, protected_uplink, opened_frame),
                "wrong logical association decrypted runtime traffic");
        SecureFrame protected_ack{};
        require(secure_hub.seal(RuntimeDirection::Downlink, runtime_plain, protected_ack) &&
                !secure_node.open(RuntimeDirection::Uplink, protected_ack, opened_frame) &&
                secure_node.open(RuntimeDirection::Downlink, protected_ack, opened_frame),
                "runtime direction separation or ACK authentication failed");
        runtime_plain.size = kMaximumSecureFrameBytes - kSecureFrameOverhead;
        require(secure_node.seal(RuntimeDirection::Uplink, runtime_plain, protected_uplink) &&
                protected_uplink.size == kMaximumSecureFrameBytes,
                "secure ESP-NOW payload boundary failed");
        ++runtime_plain.size;
        require(!secure_node.seal(RuntimeDirection::Uplink, runtime_plain, protected_uplink),
                "oversized authenticated frame was accepted");
        Key32 next_salt{};
        require(crypto.random_bytes(next_salt.data(), next_salt.size()) &&
                secure_node.start(2, next_salt) && secure_hub.start(2, next_salt) &&
                !secure_node.open(RuntimeDirection::Downlink, protected_ack, opened_frame) &&
                !secure_node.start(1, runtime_salt),
                "new runtime session accepted prior ACK or rolled back");

        Key32 wrong_code = installation_code; wrong_code[0] ^= 1;
        NodeCommissioning wrong_node(crypto, "node-a", "node-id", wrong_code);
        require(wrong_node.enable_window(100, 5000) && !wrong_node.respond(*offer, 101),
                "unapproved neighboring Hub offer was accepted");
        for (int field = 0; field < 3; ++field) {
            NodeCommissioning altered_assignment_node(crypto, "node-a", "node-id",
                                                       installation_code);
            auto altered_offer = *offer;
            if (field == 0) altered_offer.logical_id = "logical-kitchen";
            if (field == 1) altered_offer.room = "Kitchen";
            if (field == 2) altered_offer.function = "temperature";
        require(altered_assignment_node.enable_window(100, 5000) &&
                    !altered_assignment_node.respond(altered_offer, 101),
                    "altered logical assignment was accepted");
        }
        NodeCommissioning late_node(crypto, "node-a", "node-id", installation_code);
        require(late_node.enable_window(100, 5) && !late_node.respond(*offer, 106),
                "expired Node pairing window accepted offer");
        HubCommissioning wrong_key_hub(crypto, "hub-a", "hub-id", "home-id", "node-id",
                                       hub_public, installation_code, "logical-bathroom",
                                       "Bathroom", "motion");
        NodeCommissioning exact_node(crypto, "node-a", "node-id", installation_code);
        require(exact_node.enable_window(100, 5000), "exact Node test setup failed");
        const auto wrong_offer = wrong_key_hub.open(100, 5000);
        require(wrong_offer.has_value(), "wrong-key offer setup failed");
        require(!exact_node.respond(*wrong_offer, 101),
                "Node accepted an offer pinned to a different device key");
        std::cout << "P2-COM-CRYPTO HOST PASS unique keys/signatures/ECDH/HKDF/AEAD/tamper\n";
        std::cout << "P2-COM-HANDSHAKE HOST PASS exact identity/Home/Hub/window/replay\n";
        std::cout << "P2-RUNTIME-AEAD HOST PASS uplink/ACK/tamper/replay/boundary\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-COM-CRYPTO HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
