#include "firmware/hub/components/fota/hub_fota_guard.hpp"

namespace gs::hub::fota {

bool HubFotaGuard::begin(const EnrolledNode* node,
                         const security::RuntimeFrameSecurity* frames,
                         const std::string& exact_device_id,
                         std::uint32_t transfer_id) {
    if (active_ || node == nullptr || frames == nullptr || transfer_id == 0 ||
        exact_device_id.empty() || node->device_id != exact_device_id ||
        node->quarantined || node->home_id.empty() || node->hub_id.empty() ||
        node->logical_id.empty() || node->last_session == 0 ||
        frames->session() != node->last_session) return false;
    device_id_ = node->device_id;
    radio_mac_ = node->radio_mac;
    session_ = node->last_session;
    transfer_id_ = transfer_id;
    active_ = true;
    return true;
}

bool HubFotaGuard::current(const EnrolledNode* node,
                           const security::RuntimeFrameSecurity* frames) {
    if (!active_) return false;
    if (node == nullptr || frames == nullptr || node->quarantined ||
        node->device_id != device_id_ || node->radio_mac != radio_mac_ ||
        node->last_session != session_ || frames->session() != session_) {
        abort();
        return false;
    }
    return true;
}

bool HubFotaGuard::seal(const EnrolledNode* node,
                        security::RuntimeFrameSecurity* frames,
                        const gs::fota::secure_wire::Message& message,
                        security::SecureFrame& output) {
    output.size = 0;
    if (!current(node, frames) || message.transfer_id != transfer_id_ ||
        message.type == gs::fota::secure_wire::Type::Ack) return false;
    const auto encoded = gs::fota::secure_wire::encode(message);
    return encoded && frames->seal(security::RuntimeDirection::Downlink,
                                   encoded.frame, output);
}

bool HubFotaGuard::admit_verified_ack(
    const Mac& source, const EnrolledNode* node,
    const security::RuntimeFrameSecurity* frames,
    const transport::EncodedFrame& plain,
    gs::fota::secure_wire::Message& ack) {
    if (!current(node, frames) || source != radio_mac_) return false;
    const auto decoded = gs::fota::secure_wire::decode(plain.bytes.data(), plain.size);
    if (!decoded || decoded.message.type != gs::fota::secure_wire::Type::Ack ||
        decoded.message.transfer_id != transfer_id_) return false;
    ack = decoded.message;
    return true;
}

void HubFotaGuard::abort() {
    active_ = false;
    device_id_.clear();
    radio_mac_ = {};
    session_ = 0;
    transfer_id_ = 0;
}

}  // namespace gs::hub::fota
