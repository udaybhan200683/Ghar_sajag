#pragma once

#include "firmware/common/security/association_persistence.hpp"
#include "firmware/common/security/commissioning_wire.hpp"
#include "firmware/common/security/nvs_association_blob_store.hpp"
#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/node/components/storage/node_recovery_persistence.hpp"

#include <array>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>

namespace gs::node::target {

// The Node's target radio owner calls this service. It never trusts a MAC by
// itself: an unpaired offer needs the QR installation-code MAC and a matching
// private-key proof; a paired boot needs authenticated rejoin before traffic.
class NodeSecurityLink {
public:
    using Mac = std::array<std::uint8_t, 6>;
    struct Outbound {
        Mac destination{};
        security::wire::Message message;
    };

    NodeSecurityLink();
    ~NodeSecurityLink();
    NodeSecurityLink(const NodeSecurityLink&) = delete;
    NodeSecurityLink& operator=(const NodeSecurityLink&) = delete;

    // NVS must already be initialized and session must be durably allocated.
    // Missing association opens one bounded first-boot commissioning window.
    bool initialize(const Mac& physical_mac, std::uint64_t session,
                    std::uint64_t now_ms);
    std::optional<Outbound> initial_message();
    std::optional<Outbound> accept(const Mac& source, const std::uint8_t* packet,
                                    std::size_t length, std::uint64_t now_ms);
    bool ready() const { return phase_ == Phase::Ready; }
    bool faulted() const { return phase_ == Phase::Fault; }
    const security::CommissioningBinding* binding() const {
        return binding_ ? &*binding_ : nullptr;
    }
    const Mac& hub_mac() const { return hub_mac_; }
    security::RuntimeFrameSecurity* frames() { return frames_.get(); }
    bool restore_recovery(node::NodeRuntime& runtime, Milliseconds now_ms);
    bool persist_recovery(const node::NodeRuntime& runtime);

private:
    enum class Phase { Uninitialized, Commissioning, Rejoining, Ready, Fault };
    std::optional<Outbound> begin_rejoin();
    std::optional<Outbound> reply(const Mac& destination,
                                   const security::wire::Message& message);
    bool matching_hub(const Mac& source) const;

    security::TargetIdentitySigner identity_{"node", 0x7001};
    security::PsaCommissioningCrypto crypto_{identity_};
    security::NvsAssociationBlobStore store_;
    security::NvsNodeRecoveryBlobStore recovery_store_;
    security::Key32 wrapping_key_{};
    security::Key32 recovery_key_{};
    std::unique_ptr<security::AssociationRepository> repository_;
    std::unique_ptr<node::NodeRecoveryRepository> recovery_repository_;
    std::optional<security::CommissioningBinding> binding_;
    std::unique_ptr<security::NodeCommissioning> commissioning_;
    std::unique_ptr<security::NodeRejoin> rejoin_;
    std::unique_ptr<security::RuntimeFrameSecurity> frames_;
    security::wire::Assembler assembler_;
    Mac hub_mac_{};
    std::string physical_id_;
    std::uint64_t session_{0};
    Phase phase_{Phase::Uninitialized};
};

}  // namespace gs::node::target
