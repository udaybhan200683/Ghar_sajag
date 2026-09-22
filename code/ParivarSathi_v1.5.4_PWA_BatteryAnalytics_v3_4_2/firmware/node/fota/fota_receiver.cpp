#include "fota_receiver.hpp"

namespace gs::node::fota_receiver {

void Receiver::send_ack(std::uint32_t session_id, gs::fota::Status status,
                        std::uint32_t sequence) {
    gs::fota::Ack ack{};
    ack.magic = gs::fota::kMagic;
    ack.protocol_version = gs::fota::kProtocolVersion;
    ack.type = gs::fota::kAckFrameType;
    ack.session_id = session_id;
    ack.acknowledged_sequence = sequence;
    ack.next_sequence = expected_sequence_;
    ack.status = static_cast<std::int32_t>(status);
    ack.bytes_written = bytes_written_;
    callbacks_.send_ack(ack);
}

void Receiver::reset(bool abort_writer) {
    if (abort_writer && active_) writer_.abort();
    active_ = false;
    completion_requested_ = false;
    session_id_ = 0;
    expected_sequence_ = 0;
    expected_size_ = 0;
    expected_crc_ = 0;
    bytes_written_ = 0;
    running_crc_ = 0;
    last_activity_ms_ = 0;
    callbacks_.set_maintenance(false);
}

void Receiver::handle_begin(const gs::fota::Packet& packet, std::uint64_t now_ms) {
    if (active_ && session_id_ == packet.session_id) {
        send_ack(packet.session_id, gs::fota::Status::Ready, 0);
        return;
    }
    if (active_) reset(true);

    const std::size_t available = writer_.capacity();
    if (available == 0U || packet.image_size == 0U || packet.image_size > available) {
        session_id_ = packet.session_id;
        send_ack(packet.session_id,
                 available == 0U ? gs::fota::Status::OtaBegin
                                 : gs::fota::Status::BadSize,
                 0);
        reset(false);
        return;
    }
    if (!writer_.begin(packet.image_size)) {
        session_id_ = packet.session_id;
        send_ack(packet.session_id, gs::fota::Status::OtaBegin, 0);
        reset(false);
        return;
    }

    active_ = true;
    session_id_ = packet.session_id;
    expected_size_ = packet.image_size;
    expected_crc_ = packet.image_crc32;
    running_crc_ = 0xFFFFFFFFU;
    last_activity_ms_ = now_ms;
    callbacks_.set_maintenance(true);
    send_ack(packet.session_id, gs::fota::Status::Ready, 0);
}

void Receiver::handle_data(const gs::fota::Packet& packet) {
    if (!active_ || packet.session_id != session_id_) {
        send_ack(packet.session_id, gs::fota::Status::BadSession, packet.sequence);
        return;
    }
    if (packet.sequence < expected_sequence_) {
        send_ack(packet.session_id, gs::fota::Status::Duplicate, packet.sequence);
        return;
    }
    if (packet.sequence != expected_sequence_) {
        send_ack(packet.session_id, gs::fota::Status::BadSequence, packet.sequence);
        return;
    }
    if (packet.payload_length == 0U || packet.payload_length > gs::fota::kChunkBytes ||
        bytes_written_ + packet.payload_length > expected_size_) {
        send_ack(packet.session_id, gs::fota::Status::BadSize, packet.sequence);
        return;
    }
    if (gs::fota::crc32(packet.payload, packet.payload_length) != packet.payload_crc32) {
        send_ack(packet.session_id, gs::fota::Status::BadCrc, packet.sequence);
        return;
    }
    if (!writer_.write(packet.payload, packet.payload_length)) {
        send_ack(packet.session_id, gs::fota::Status::OtaWrite, packet.sequence);
        reset(true);
        return;
    }
    running_crc_ = gs::fota::crc32_update(running_crc_, packet.payload,
                                           packet.payload_length);
    bytes_written_ += packet.payload_length;
    ++expected_sequence_;
    send_ack(packet.session_id, gs::fota::Status::DataOk, packet.sequence);
}

void Receiver::handle_end(const gs::fota::Packet& packet) {
    if (!active_ || packet.session_id != session_id_) {
        send_ack(packet.session_id, gs::fota::Status::BadSession, packet.sequence);
        return;
    }
    if (bytes_written_ != expected_size_) {
        send_ack(packet.session_id, gs::fota::Status::BadSize, packet.sequence);
        return;
    }
    if ((running_crc_ ^ 0xFFFFFFFFU) != expected_crc_) {
        send_ack(packet.session_id, gs::fota::Status::BadCrc, packet.sequence);
        reset(true);
        return;
    }
    if (!writer_.finalize()) {
        send_ack(packet.session_id, gs::fota::Status::OtaEnd, packet.sequence);
        reset(false);
        return;
    }
    if (!writer_.commit_boot()) {
        send_ack(packet.session_id, gs::fota::Status::SetBoot, packet.sequence);
        reset(false);
        return;
    }
    completion_requested_ = true;
    send_ack(packet.session_id, gs::fota::Status::Complete, packet.sequence);
    callbacks_.request_restart();
}

bool Receiver::process(const gs::fota::Packet& packet, std::uint64_t now_ms) {
    if (packet.magic != gs::fota::kMagic ||
        packet.protocol_version != gs::fota::kProtocolVersion) return false;
    if (active_ && packet.session_id == session_id_) last_activity_ms_ = now_ms;
    switch (static_cast<gs::fota::MessageType>(packet.type)) {
        case gs::fota::MessageType::Begin: handle_begin(packet, now_ms); break;
        case gs::fota::MessageType::Data: handle_data(packet); break;
        case gs::fota::MessageType::End: handle_end(packet); break;
        case gs::fota::MessageType::Abort:
            if (active_ && packet.session_id == session_id_) reset(true);
            break;
        default:
            send_ack(packet.session_id, gs::fota::Status::BadPacket, packet.sequence);
            break;
    }
    return true;
}

void Receiver::poll(std::uint64_t now_ms) {
    if (active_ && now_ms - last_activity_ms_ >= kInactivityTimeoutMs) {
        callbacks_.report_timeout();
        reset(true);
    }
}

Snapshot Receiver::snapshot() const {
    return {active_, completion_requested_, session_id_, expected_sequence_,
            expected_size_, bytes_written_};
}

}  // namespace gs::node::fota_receiver
