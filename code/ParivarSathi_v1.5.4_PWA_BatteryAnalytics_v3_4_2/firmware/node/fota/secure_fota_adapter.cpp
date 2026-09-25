#include "firmware/node/fota/secure_fota_adapter.hpp"

#include <algorithm>
#include <cstring>

namespace gs::node::fota_receiver {

void SecureFotaAdapter::abort_transfer(std::uint64_t now_ms) {
    if (active_) {
        gs::fota::Packet stop{};
        stop.magic = gs::fota::kMagic;
        stop.protocol_version = gs::fota::kProtocolVersion;
        stop.type = static_cast<std::uint8_t>(gs::fota::MessageType::Abort);
        stop.session_id = transfer_id_;
        (void)receiver_.process(stop, now_ms);
    }
    digest_.abort();
    active_ = false;
    digest_complete_ = false;
}

bool SecureFotaAdapter::process(const gs::fota::secure_wire::Message& message,
                                std::uint64_t authenticated_session,
                                std::uint64_t now_ms) {
    using gs::fota::secure_wire::Type;
    if (authenticated_session == 0 || message.transfer_id == 0 ||
        message.type == Type::Ack) return false;
    // The decoder enforces bounds, but retain a local check at the OTA boundary.
    if (message.type == Type::Data &&
        (message.data_size == 0 ||
         message.data_size > gs::fota::secure_wire::kMaxChunkBytes)) return false;
    if (message.type == Type::Begin) {
        if (receiver_.snapshot().completion_requested) return false;
        if (message.index != 0 ||
            message.board_size > gs::fota::secure_wire::kMaxClaimBytes ||
            message.version_size > gs::fota::secure_wire::kMaxClaimBytes ||
            message.board_size != board_.size() ||
            std::memcmp(message.board.data(), board_.data(), board_.size()) != 0 ||
            message.version_size == 0 || message.image_size == 0) return false;
        if (active_ && (authenticated_session != authenticated_session_ ||
                        message.transfer_id != transfer_id_ ||
                        message.image_size != image_size_ ||
                        message.image_crc32 != image_crc32_ ||
                        message.image_sha256 != image_sha256_ ||
                        message.version_size != version_size_ ||
                        !std::equal(message.version.begin(),
                                    message.version.begin() + message.version_size,
                                    version_.begin()))) return false;
    } else if (!active_ || authenticated_session != authenticated_session_ ||
               message.transfer_id != transfer_id_) {
        return false;
    }

    gs::fota::Packet packet{};
    packet.magic = gs::fota::kMagic;
    packet.protocol_version = gs::fota::kProtocolVersion;
    packet.session_id = message.transfer_id;
    packet.sequence = message.index;
    packet.image_size = message.type == Type::Begin ? message.image_size : image_size_;
    packet.image_crc32 = message.type == Type::Begin ? message.image_crc32 : image_crc32_;
    switch (message.type) {
        case Type::Begin:
            packet.type = static_cast<std::uint8_t>(gs::fota::MessageType::Begin);
            break;
        case Type::Data:
            packet.type = static_cast<std::uint8_t>(gs::fota::MessageType::Data);
            packet.payload_length = message.data_size;
            std::copy_n(message.data.data(), message.data_size, packet.payload);
            packet.payload_crc32 = gs::fota::crc32(packet.payload, packet.payload_length);
            break;
        case Type::End:
            packet.type = static_cast<std::uint8_t>(gs::fota::MessageType::End);
            break;
        case Type::Abort:
            packet.type = static_cast<std::uint8_t>(gs::fota::MessageType::Abort);
            break;
        case Type::Ack:
            return false;
    }
    if (message.type == Type::Begin && !active_ && !digest_.start()) return false;
    const auto before = receiver_.snapshot();
    if (message.type == Type::End && !digest_complete_ &&
        before.bytes_written == image_size_) {
        std::array<std::uint8_t, 32> actual{};
        if (!digest_.finish(actual) || actual != image_sha256_) {
            abort_transfer(now_ms);
            return false;
        }
        digest_complete_ = true;
    }
    const bool accepted = receiver_.process(packet, now_ms);
    if (message.type == Type::Begin && accepted && receiver_.snapshot().active) {
        active_ = true;
        transfer_id_ = message.transfer_id;
        authenticated_session_ = authenticated_session;
        image_size_ = message.image_size;
        image_crc32_ = message.image_crc32;
        image_sha256_ = message.image_sha256;
        version_ = message.version;
        version_size_ = message.version_size;
        digest_complete_ = false;
    } else if (message.type == Type::Begin && !receiver_.snapshot().active) {
        digest_.abort();
    } else if (message.type == Type::Data && active_) {
        const auto after = receiver_.snapshot();
        if (after.bytes_written > before.bytes_written) {
            if (!digest_.add(message.data.data(), message.data_size)) {
                abort_transfer(now_ms);
                return false;
            }
        } else if (!after.active) {
            digest_.abort();
            active_ = false;
        }
    } else if (message.type == Type::Abort && accepted) {
        digest_.abort();
        active_ = false;
        digest_complete_ = false;
    } else if (message.type == Type::End && !receiver_.snapshot().active) {
        digest_.abort();
        active_ = false;
    }
    return accepted;
}

void SecureFotaAdapter::poll(std::uint64_t now_ms) {
    receiver_.poll(now_ms);
    const auto snapshot = receiver_.snapshot();
    if (!snapshot.active && !snapshot.completion_requested && active_) {
        digest_.abort();
        active_ = false;
        digest_complete_ = false;
    }
}

}  // namespace gs::node::fota_receiver
