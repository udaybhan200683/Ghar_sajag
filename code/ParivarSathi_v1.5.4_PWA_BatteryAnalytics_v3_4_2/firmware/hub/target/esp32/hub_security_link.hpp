#pragma once

#include "firmware/common/security/commissioning_wire.hpp"
#include "firmware/common/security/nvs_association_blob_store.hpp"
#include "firmware/common/security/psa_commissioning_crypto.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/security/target_identity_signer.hpp"
#include "firmware/hub/components/registry/registry_persistence.hpp"
#include "firmware/hub/components/storage/journal.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace gs::hub::target {

class HubSecurityLink {
public:
    using Mac = std::array<std::uint8_t, 6>;
    static constexpr std::size_t kInstalledCapacity = 10;
    struct ExpectedNode {
        Mac radio_mac{};
        std::string device_id;
        security::P256PublicKey public_key{};
        security::Key32 installer_code{};
        std::string logical_id;
        std::string room;
        std::string function;
    };
    struct Outbound {
        Mac destination{};
        security::wire::Message message;
    };
    struct Removal {
        RegistryResult result{RegistryResult::UnknownDevice};
        Mac radio_mac{};
        std::string logical_id;
        bool access_stopped{false};
    };

    HubSecurityLink();
    ~HubSecurityLink();
    HubSecurityLink(const HubSecurityLink&) = delete;
    HubSecurityLink& operator=(const HubSecurityLink&) = delete;
    bool initialize(const Mac& hub_mac);
    // Attach the existing bounded encrypted event journal using a key derived
    // from this Hub/Home wrapping key. Failure keeps event admission closed.
    bool attach_event_journal(hub::HubJournal& journal,
                              hub::JournalSlotStore& store);
    std::optional<Outbound> begin_commissioning(const ExpectedNode& exact,
                                                 std::uint64_t now_ms);
    std::optional<Outbound> accept(const Mac& source, const std::uint8_t* packet,
                                    std::size_t length, std::uint64_t now_ms);
    std::optional<Mac> expire_candidate(std::uint64_t now_ms);
    // Called only by the Hub owner after a locally authorized service request.
    // The revocation/quarantine snapshot commits before live access is cut off.
    Removal remove_node(const std::string& device_id);
    const hub::EnrolledNode* ready_node(const Mac& source) const;
    security::RuntimeFrameSecurity* frames_for(const Mac& source);
    std::vector<Mac> enrolled_macs() const;
    const std::string& home_id() const { return home_id_; }
    const std::string& hub_id() const { return hub_id_; }
    bool faulted() const { return faulted_; }

private:
    struct PendingRejoin {
        security::CommissioningBinding binding;
        security::HubRejoin protocol;
        bool committed{false};
        PendingRejoin(security::CommissioningCrypto& crypto,
                      const security::CommissioningBinding& value,
                      std::uint64_t last_session)
            : binding(value), protocol(crypto, binding, last_session) {}
    };
    struct ActiveSession {
        hub::EnrolledNode record;
        std::unique_ptr<security::RuntimeFrameSecurity> frames;
    };
    bool persist_candidate(hub::NodeRegistry& candidate,
                            const std::vector<security::CommissioningBinding>& bindings);
    std::optional<Outbound> reply(const Mac& destination,
                                   const security::wire::Message& message);
    const security::CommissioningBinding* binding_for(const std::string& device_id) const;
    bool expected_source(const Mac& source) const;

    security::TargetIdentitySigner identity_{"hub", 0x7001};
    security::PsaCommissioningCrypto crypto_{identity_};
    security::NvsRegistryBlobStore store_;
    security::Key32 wrapping_key_{};
    security::Key32 journal_key_{};
    security::P256PublicKey hub_public_key_{};
    std::unique_ptr<hub::HubRegistryRepository> repository_;
    std::unique_ptr<hub::NodeRegistry> registry_;
    std::vector<security::CommissioningBinding> bindings_;
    std::unique_ptr<security::HubCommissioning> commissioning_;
    std::optional<ExpectedNode> expected_;
    std::map<Mac, security::wire::Assembler> assemblers_;
    std::map<Mac, std::unique_ptr<PendingRejoin>> rejoining_;
    std::map<Mac, ActiveSession> active_;
    std::string home_id_;
    std::string hub_id_;
    std::uint64_t pairing_deadline_ms_{0};
    bool faulted_{false};
};

}  // namespace gs::hub::target
