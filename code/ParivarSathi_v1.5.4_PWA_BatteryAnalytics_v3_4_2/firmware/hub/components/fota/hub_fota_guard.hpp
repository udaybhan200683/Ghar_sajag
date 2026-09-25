#pragma once

#include "firmware/common/transport/fota_secure_wire.hpp"
#include "firmware/hub/components/registry/node_registry.hpp"

#include <array>
#include <cstdint>
#include <string>

namespace gs::hub::fota {

// Transaction metadata only. RuntimeFrameSecurity remains owned by the Hub
// security owner and is supplied to each operation; this class never owns keys.
class HubFotaGuard {
public:
    using Mac = std::array<std::uint8_t, 6>;
    bool begin(const EnrolledNode* node, const security::RuntimeFrameSecurity* frames,
               const std::string& exact_device_id, std::uint32_t transfer_id);
    bool current(const EnrolledNode* node, const security::RuntimeFrameSecurity* frames);
    bool seal(const EnrolledNode* node, security::RuntimeFrameSecurity* frames,
              const gs::fota::secure_wire::Message& message,
              security::SecureFrame& output);
    // Called only after the owner opened AEAD exactly once. Other plaintext
    // (events/health) must remain available to its normal dispatcher.
    bool admit_verified_ack(const Mac& source, const EnrolledNode* node,
                            const security::RuntimeFrameSecurity* frames,
                            const transport::EncodedFrame& plain,
                            gs::fota::secure_wire::Message& ack);
    void abort();
    bool active() const { return active_; }
    std::uint64_t session() const { return session_; }
    const std::string& device_id() const { return device_id_; }
    const Mac& radio_mac() const { return radio_mac_; }
    std::uint32_t transfer_id() const { return transfer_id_; }

private:
    bool active_{false};
    std::string device_id_;
    Mac radio_mac_{};
    std::uint64_t session_{0};
    std::uint32_t transfer_id_{0};
};

}  // namespace gs::hub::fota
