#pragma once
// GS-150 deterministic owner/transport simulation using production policy,
// NodeRuntime, encrypted recovery, AEAD/rejoin, persistent HubRuntime and PIR.
// RF/flash/OS costs are explicit model inputs, never physical measurements.
#include "power/power.hpp"
#include "power/session_recovery_policy.hpp"
#include "sensing/sensing.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/node/storage/node_recovery_persistence.hpp"
#include "firmware/node/target/esp32c3/node_target_config.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/rejoin_protocol.hpp"
#include "tests/support/host/security/openssl_commissioning_crypto.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <memory>
#include <map>
#include <stdexcept>
#include <vector>

using namespace gs;
using namespace gs::node;
using namespace gs::security;
using gs::host::security::OpenSslCommissioningCrypto;
namespace {
unsigned checks = 0;
void require(bool yes, const char* message) {
    ++checks;
    if (!yes) throw std::runtime_error(message);
}
struct Blob : SecurityBlobStore {
    Bytes data;
    unsigned writes = 0;
    bool fail = false;
    bool read(Bytes& out, bool& found) override { out = data; found = !data.empty(); return true; }
    bool write(const Bytes& in) override {
        if (fail) return false;
        data = in; ++writes; return true;
    }
};
struct Slots : hub::JournalSlotStore {
    std::array<Bytes, 128> data;
    bool read(std::size_t slot, Bytes& out, bool& found) override {
        if (slot >= data.size()) return false;
        out = data[slot]; found = !out.empty(); return true;
    }
    bool write(std::size_t slot, const Bytes& in) override {
        if (slot >= data.size()) return false;
        data[slot] = in; return true;
    }
};
struct Pair {
    OpenSslCommissioningCrypto crypto;
    CommissioningBinding binding;
    Key32 key{};
    Blob blob;
    Slots slots;
    std::unique_ptr<NodeRecoveryRepository> repository;
    std::unique_ptr<NodeRuntime> node;
    std::unique_ptr<hub::HubRuntime> hub;
    std::unique_ptr<RuntimeFrameSecurity> nf, hf;
    std::uint64_t session = 10;
    Pair() {
        binding.device_id = "device"; binding.logical_id = "room";
        binding.home_id = "home"; binding.hub_id = "hub";
        binding.installation_key.fill(9); key.fill(7);
        repository = std::make_unique<NodeRecoveryRepository>(crypto, blob, key, "home", "hub", "room");
        node = std::make_unique<NodeRuntime>("room", session);
        nf = std::make_unique<RuntimeFrameSecurity>(crypto, binding);
        hf = std::make_unique<RuntimeFrameSecurity>(crypto, binding);
        reboot_hub();
        rejoin(session);
    }
    void reboot_hub() {
        hub = std::make_unique<hub::HubRuntime>(32, 128);
        RoutineConfig config; config.window_id = "day"; config.end_at = 2000000000;
        hub->authorize_node("room", session, true);
        hub->start_window(config, HomeMode::Home);
        require(hub->journal().attach_persistence(crypto, slots, key), "Hub journal recovery");
        require(hub->restore_from_journal(), "Hub reducer recovery");
    }
    void rejoin(std::uint64_t next) {
        NodeRejoin nr(crypto, binding, next, 2);
        HubRejoin hr(crypto, binding, next - 1);
        const auto hello = nr.begin();
        require(hello.has_value(), "rejoin Hello");
        const auto challenge = hr.accept(*hello);
        require(challenge.has_value(), "authenticated challenge");
        const auto final = nr.accept(*challenge);
        require(final.has_value(), "bound Final");
        const auto ack = hr.confirm(*final);
        require(ack && nr.commit(*ack), "authenticated session installation");
        require(nf->start(next, *nr.session_salt()) && hf->start(next, *hr.session_salt()), "fresh AEAD contexts");
        session = next; hub->authorize_node("room", session, true);
    }
    EventKey admit(EventKind kind, Milliseconds now) {
        const auto k = node->record(kind, "room", now, 1700000000 + now / 1000);
        require(k.has_value(), "event admission");
        require(repository->save(node->recovery_snapshot()), "durable before exposure");
        return *k;
    }
    SecureFrame deliver(const NodeMessage& msg, Milliseconds now, bool& changed) {
        const auto encoded = transport::encode_node_message(msg);
        SecureFrame wire;
        transport::EncodedFrame opened;
        require(encoded && nf->seal(RuntimeDirection::Uplink, encoded.frame, wire) &&
                hf->open(RuntimeDirection::Uplink, wire, opened), "authenticated new frame for exact-key replay");
        const auto decoded = transport::decode_node_message(opened.bytes.data(), opened.size);
        require(decoded && hub->authenticated_radio_message_callback(*decoded.value,
            "room", "device", session, 1700000000 + now / 1000,
            static_cast<std::uint64_t>(now)), "authenticated owner admission");
        const auto processed = hub->run_state_once();
        require(processed && processed->ack == AckClass::Durable, "durable before application ACK");
        changed = processed->state_changed;
        NodeAckMessage ack; ack.node_id=msg.node_id; ack.session_id=msg.session_id;
        ack.sequence_number=msg.sequence_number; ack.ack_type=processed->ack;
        const auto reply = transport::encode_node_ack(ack);
        SecureFrame protected_ack;
        require(reply && hf->seal(RuntimeDirection::Downlink, reply.frame, protected_ack), "seal Durable ACK");
        return protected_ack;
    }
    bool ack(const SecureFrame& wire) {
        transport::EncodedFrame plain;
        if (!nf->open(RuntimeDirection::Downlink, wire, plain)) return false;
        const auto decoded = transport::decode_node_ack(plain.bytes.data(), plain.size);
        if (!decoded) return false;
        EventKey k{decoded.value->node_id, decoded.value->session_id, decoded.value->sequence_number};
        if (!node->acknowledge(k, decoded.value->ack_type)) return false;
        require(repository->save(node->recovery_snapshot()), "durable ACK retirement");
        return true;
    }
    void reboot_node(Milliseconds now) {
        const auto saved = repository->load();
        require(saved.state.has_value(), "load encrypted pending snapshot");
        const auto next = session + 1;
        node = std::make_unique<NodeRuntime>("room", next);
        require(node->restore_recovery(*saved.state, now), "Node reboot retains original identity");
        require(repository->save(node->recovery_snapshot()), "new boot snapshot");
        rejoin(next);
    }
};
LightSleepObservation observation(Milliseconds now) {
    LightSleepObservation o;
    o.now_ms = now; o.next_health_ms = now + 120000;
    o.authenticated = o.product_ready = o.persistence_clean = true;
    o.pir_high = false; o.pir_low_stable = o.debounce_safe = true;
    o.wake_source_ready = o.runtime_state_known = true;
    return o;
}
}
