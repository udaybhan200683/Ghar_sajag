#include "firmware/node/fota/secure_fota_adapter.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

struct Writer final : gs::node::fota_receiver::IOtaWriter {
    std::vector<std::uint8_t> image;
    bool begun{false};
    bool committed{false};
    bool aborted{false};
    std::size_t capacity() override { return 4096; }
    bool begin(std::size_t) override { begun = true; return true; }
    bool write(const std::uint8_t* data, std::size_t size) override {
        image.insert(image.end(), data, data + size); return true;
    }
    bool finalize() override { return true; }
    bool commit_boot() override { committed = true; return true; }
    void abort() override { aborted = true; }
};

struct Callbacks final : gs::node::fota_receiver::IReceiverCallbacks {
    gs::fota::Ack last{};
    bool maintenance{false};
    unsigned restarts{0};
    unsigned timeouts{0};
    void send_ack(const gs::fota::Ack& ack) override { last = ack; }
    void set_maintenance(bool active) override { maintenance = active; }
    void report_timeout() override { ++timeouts; }
    void request_restart() override { ++restarts; }
    gs::fota::Status status() const { return static_cast<gs::fota::Status>(last.status); }
};
}

int main() {
    using namespace gs;
    using namespace gs::fota::secure_wire;
    host::security::OpenSslCommissioningCrypto crypto;
    security::CommissioningBinding binding;
    binding.device_id = "c3-010203040506";
    binding.hub_id = "hub-1";
    binding.home_id = "home-1";
    binding.logical_id = "bathroom";
    binding.installation_key.fill(0x42);
    security::RuntimeFrameSecurity hub(crypto, binding), node(crypto, binding);
    security::Key32 salt{}; salt.fill(0x51);
    require(hub.start(7, salt) && node.start(7, salt), "session startup");
    Writer writer;
    Callbacks callbacks;
    node::fota_receiver::Receiver receiver(writer, callbacks);
    node::fota_receiver::SecureFotaAdapter adapter(receiver, "esp32c3");
    const auto deliver = [&](const Message& message) {
        const auto encoded = encode(message);
        security::SecureFrame protected_frame;
        transport::EncodedFrame opened;
        require(encoded && hub.seal(security::RuntimeDirection::Downlink,
                                    encoded.frame, protected_frame) &&
                node.open(security::RuntimeDirection::Downlink,
                          protected_frame, opened), "secure delivery failed");
        const auto decoded = decode(opened.bytes.data(), opened.size);
        require(static_cast<bool>(decoded), "secure FOTA decode failed");
        return adapter.process(decoded.message, 7, 100);
    };
    std::vector<std::uint8_t> image(193);
    for (std::size_t i = 0; i < image.size(); ++i)
        image[i] = static_cast<std::uint8_t>(i);
    Message begin;
    begin.type = Type::Begin;
    begin.transfer_id = 81;
    begin.image_size = image.size();
    begin.image_crc32 = fota::crc32(image.data(), image.size());
    begin.board_size = 7;
    std::copy_n("esp32c3", 7, begin.board.begin());
    begin.version_size = 3;
    std::copy_n("2.0", 3, begin.version.begin());
    Message wrong_board = begin;
    wrong_board.board[0] = 'x';
    require(!deliver(wrong_board) && !writer.begun, "wrong board started OTA");
    require(deliver(begin) && writer.begun && callbacks.maintenance &&
            callbacks.status() == fota::Status::Ready, "valid Begin rejected");
    Message altered_claim = begin;
    altered_claim.image_sha256[0] ^= 1;
    require(!deliver(altered_claim), "changed image digest accepted mid-transfer");
    altered_claim = begin;
    altered_claim.version[0] = '3';
    require(!deliver(altered_claim), "changed image version accepted mid-transfer");
    require(!adapter.process(begin, 8, 101), "different session accepted");
    Message wrong_transfer = begin;
    wrong_transfer.transfer_id = 82;
    require(!deliver(wrong_transfer), "parallel transfer replaced active OTA");
    Message data;
    data.type = Type::Data;
    data.transfer_id = 81;
    data.data_size = 192;
    std::copy_n(image.begin(), 192, data.data.begin());
    require(deliver(data) && callbacks.status() == fota::Status::DataOk,
            "192-byte authenticated chunk rejected");
    require(deliver(data) && callbacks.status() == fota::Status::Duplicate &&
            writer.image.size() == 192, "duplicate chunk wrote twice");
    data.index = 1;
    data.data_size = 1;
    data.data[0] = image.back();
    require(deliver(data) && writer.image == image, "second chunk not written");
    Message end;
    end.type = Type::End;
    end.transfer_id = 81;
    end.index = 2;
    require(deliver(end) && writer.committed && callbacks.restarts == 1 &&
            callbacks.status() == fota::Status::Complete,
            "authenticated transfer did not complete");

    Message completed_ack;
    completed_ack.type = Type::Ack;
    completed_ack.transfer_id = callbacks.last.session_id;
    completed_ack.index = callbacks.last.acknowledged_sequence;
    completed_ack.ack_status = callbacks.status();
    completed_ack.next_index = callbacks.last.next_sequence;
    completed_ack.bytes_written = callbacks.last.bytes_written;
    const auto ack_plain = encode(completed_ack);
    security::SecureFrame protected_ack;
    transport::EncodedFrame opened_ack;
    require(ack_plain && node.seal(security::RuntimeDirection::Uplink,
                                   ack_plain.frame, protected_ack) &&
            hub.open(security::RuntimeDirection::Uplink,
                     protected_ack, opened_ack), "authenticated FOTA ACK failed");
    const auto decoded_ack = decode(opened_ack.bytes.data(), opened_ack.size);
    require(static_cast<bool>(decoded_ack) && decoded_ack.message.type == Type::Ack &&
            decoded_ack.message.transfer_id == 81 &&
            decoded_ack.message.index == 2 &&
            decoded_ack.message.ack_status == fota::Status::Complete &&
            decoded_ack.message.bytes_written == image.size(),
            "completed ACK lost transfer or byte accounting");
    require(!hub.open(security::RuntimeDirection::Uplink,
                      protected_ack, opened_ack), "replayed FOTA ACK opened");

    security::SecureFrame protected_frame;
    transport::EncodedFrame opened;
    const auto encoded = encode(end);
    require(hub.seal(security::RuntimeDirection::Downlink,
                     encoded.frame, protected_frame), "seal replay fixture");
    auto tampered = protected_frame;
    tampered.bytes[tampered.size - 1] ^= 1;
    require(!node.open(security::RuntimeDirection::Downlink, tampered, opened),
            "tampered packet opened");
    require(node.open(security::RuntimeDirection::Downlink, protected_frame, opened) &&
            !node.open(security::RuntimeDirection::Downlink, protected_frame, opened),
            "replayed packet opened");

    Writer timeout_writer;
    Callbacks timeout_callbacks;
    node::fota_receiver::Receiver timeout_receiver(timeout_writer, timeout_callbacks);
    node::fota_receiver::SecureFotaAdapter timeout_adapter(timeout_receiver, "esp32c3");
    require(timeout_adapter.process(begin, 7, 100), "timeout Begin rejected");
    timeout_adapter.poll(100 + node::fota_receiver::Receiver::kInactivityTimeoutMs);
    require(!timeout_adapter.active() && timeout_writer.aborted &&
            timeout_callbacks.timeouts == 1, "timeout did not abort OTA");
    std::cout << "P2-FOTA-S3-ADAPTER HOST PASS\n";
}
