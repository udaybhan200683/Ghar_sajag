#include "firmware/hub/components/fota/hub_fota_guard.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

int main() {
    using namespace gs;
    host::security::OpenSslCommissioningCrypto crypto;
    security::CommissioningBinding binding;
    binding.device_id = "c3-010203040506";
    binding.hub_id = "hub-1";
    binding.home_id = "home-1";
    binding.logical_id = "bathroom";
    binding.installation_key.fill(0x42);
    security::RuntimeFrameSecurity hub_frames(crypto, binding);
    security::RuntimeFrameSecurity node_frames(crypto, binding);
    security::Key32 salt{}; salt.fill(0x51);
    require(hub_frames.start(7, salt) && node_frames.start(7, salt), "session startup failed");
    hub::EnrolledNode record;
    record.device_id = binding.device_id;
    record.hub_id = binding.hub_id;
    record.home_id = binding.home_id;
    record.logical_id = binding.logical_id;
    record.room = "bathroom";
    record.function = "motion";
    record.p256_public_key[0] = 0x04;
    record.radio_mac = {1,2,3,4,5,6};
    record.last_session = 7;
    hub::fota::HubFotaGuard guard;
    require(!guard.begin(nullptr, &hub_frames, record.device_id, 11), "unknown accepted");
    require(!guard.begin(&record, nullptr, record.device_id, 11), "no session accepted");
    require(!guard.begin(&record, &hub_frames, "another-device", 11), "wrong identity accepted");
    record.quarantined = true;
    require(!guard.begin(&record, &hub_frames, record.device_id, 11), "quarantined accepted");
    record.quarantined = false;
    require(guard.begin(&record, &hub_frames, record.device_id, 11), "enrolled node rejected");
    require(!guard.begin(&record, &hub_frames, record.device_id, 12), "parallel transfer accepted");

    fota::secure_wire::Message message;
    message.type = fota::secure_wire::Type::Data;
    message.transfer_id = 11;
    message.data_size = 1;
    message.data[0] = 9;
    security::SecureFrame outbound;
    require(guard.seal(&record, &hub_frames, message, outbound) && outbound.size <= 250,
            "Hub owner could not seal FOTA packet");
    transport::EncodedFrame opened;
    require(node_frames.open(security::RuntimeDirection::Downlink, outbound, opened) &&
            fota::secure_wire::decode(opened.bytes.data(), opened.size),
            "Node could not authenticate Hub packet");
    message.transfer_id = 12;
    require(!guard.seal(&record, &hub_frames, message, outbound), "wrong transfer sent");

    message.type = fota::secure_wire::Type::Ack;
    message.transfer_id = 11;
    message.ack_status = fota::Status::DataOk;
    const auto ack_plain = fota::secure_wire::encode(message);
    security::SecureFrame ack_frame;
    require(ack_plain && node_frames.seal(security::RuntimeDirection::Uplink,
                                   ack_plain.frame, ack_frame), "ACK seal failed");
    fota::secure_wire::Message verified;
    const auto wrong_mac = hub::fota::HubFotaGuard::Mac{6,5,4,3,2,1};
    transport::EncodedFrame ack_plaintext;
    require(hub_frames.open(security::RuntimeDirection::Uplink, ack_frame, ack_plaintext),
            "valid protected ACK rejected");
    require(!guard.admit_verified_ack(wrong_mac, &record, &hub_frames,
                                     ack_plaintext, verified), "wrong Node ACK accepted");
    auto tampered = ack_frame; tampered.bytes[tampered.size-1] ^= 1;
    require(!hub_frames.open(security::RuntimeDirection::Uplink, tampered, opened),
            "tampered ACK accepted");
    require(guard.admit_verified_ack(record.radio_mac, &record, &hub_frames,
                                     ack_plaintext, verified) &&
            verified.transfer_id == 11 && verified.ack_status == fota::Status::DataOk,
            "verified ACK not forwarded");
    require(!hub_frames.open(security::RuntimeDirection::Uplink, ack_frame, opened),
            "replayed ACK accepted");

    message.transfer_id = 12;
    const auto wrong_transfer = fota::secure_wire::encode(message);
    require(node_frames.seal(security::RuntimeDirection::Uplink,
                      wrong_transfer.frame, ack_frame) &&
            hub_frames.open(security::RuntimeDirection::Uplink, ack_frame, ack_plaintext) &&
            !guard.admit_verified_ack(record.radio_mac, &record, &hub_frames,
                                      ack_plaintext, verified),
            "wrong transfer ACK accepted");
    record.last_session = 8;
    require(!guard.current(&record, &hub_frames) && !guard.active(),
            "session change did not abort");
    require(!guard.admit_verified_ack(record.radio_mac, &record, &hub_frames,
                                      ack_plaintext, verified),
            "stale session ACK accepted");
    record.last_session = 7;
    require(guard.begin(&record, &hub_frames, record.device_id, 13), "restart rejected");
    record.quarantined = true;
    require(!guard.current(&record, &hub_frames) && !guard.active(),
            "revoked/quarantined access remained active");
    record.quarantined = false;
    hub::NodeRegistry registry(binding.home_id, binding.hub_id, 10, 10);
    require(registry.enroll(record) == hub::RegistryResult::Accepted,
            "registry fixture enrollment failed");
    require(registry.remove(record.device_id) == hub::RegistryResult::Accepted &&
            registry.is_revoked(record.device_id), "registry revocation failed");
    const auto revoked = registry.find(record.device_id);
    require(!revoked && !guard.begin(revoked ? &*revoked : nullptr,
                                     &hub_frames, record.device_id, 14),
            "revoked physical identity accepted");
    std::cout << "P2-FOTA-S2-GUARD HOST PASS\n";
}
