#include "firmware/common/transport/fota_secure_wire.hpp"

#include <algorithm>
#include <cstring>

namespace gs::fota::secure_wire {
namespace {
constexpr std::uint8_t kMagic0 = 'G';
constexpr std::uint8_t kMagic1 = 'F';
constexpr std::uint8_t kVersion = 2;

void put16(std::uint8_t* out, std::uint16_t value) {
    out[0] = static_cast<std::uint8_t>(value >> 8);
    out[1] = static_cast<std::uint8_t>(value);
}
void put32(std::uint8_t* out, std::uint32_t value) {
    for (int i = 0; i < 4; ++i)
        out[i] = static_cast<std::uint8_t>(value >> (24 - 8 * i));
}
std::uint16_t get16(const std::uint8_t* in) {
    return static_cast<std::uint16_t>((static_cast<std::uint16_t>(in[0]) << 8) | in[1]);
}
std::uint32_t get32(const std::uint8_t* in) {
    std::uint32_t value = 0;
    for (int i = 0; i < 4; ++i) value = (value << 8) | in[i];
    return value;
}
bool valid_type(Type type) {
    return type == Type::Begin || type == Type::Data || type == Type::End ||
           type == Type::Abort || type == Type::Ack;
}
bool valid_status(Status status) {
    switch (status) {
        case Status::Ready: case Status::DataOk: case Status::Complete:
        case Status::Duplicate: case Status::BadPacket: case Status::BadSession:
        case Status::BadSequence: case Status::BadCrc: case Status::BadSize:
        case Status::OtaBegin: case Status::OtaWrite: case Status::OtaEnd:
        case Status::SetBoot: return true;
    }
    return false;
}
bool parse_status(std::uint32_t wire, Status& status) {
    constexpr std::array<Status, 13> values{
        Status::Ready, Status::DataOk, Status::Complete, Status::Duplicate,
        Status::BadPacket, Status::BadSession, Status::BadSequence,
        Status::BadCrc, Status::BadSize, Status::OtaBegin, Status::OtaWrite,
        Status::OtaEnd, Status::SetBoot};
    for (const auto candidate : values) {
        if (wire == static_cast<std::uint32_t>(candidate)) {
            status = candidate;
            return true;
        }
    }
    return false;
}
bool valid_claim(const char* bytes, std::size_t size) {
    if (size == 0 || size > kMaxClaimBytes) return false;
    for (std::size_t i = 0; i < size; ++i)
        if (static_cast<unsigned char>(bytes[i]) < 0x21 ||
            static_cast<unsigned char>(bytes[i]) > 0x7e) return false;
    return true;
}
}  // namespace

EncodeResult encode(const Message& message) {
    EncodeResult result;
    if (!valid_type(message.type) || message.transfer_id == 0) {
        result.error = Error::InvalidValue;
        return result;
    }
    std::size_t body_size = 0;
    switch (message.type) {
        case Type::Begin:
            if (message.index != 0 || message.image_size == 0 ||
                !valid_claim(message.board.data(), message.board_size) ||
                !valid_claim(message.version.data(), message.version_size)) {
                result.error = Error::MalformedBody;
                return result;
            }
            body_size = kBeginFixedBytes + message.board_size + message.version_size;
            break;
        case Type::Data:
            if (message.data_size == 0 || message.data_size > kMaxChunkBytes) {
                result.error = message.data_size > kMaxChunkBytes
                    ? Error::TooLarge : Error::MalformedBody;
                return result;
            }
            body_size = message.data_size;
            break;
        case Type::End: case Type::Abort: break;
        case Type::Ack:
            if (!valid_status(message.ack_status)) {
                result.error = Error::MalformedBody;
                return result;
            }
            body_size = kAckBodyBytes;
            break;
    }
    const std::size_t total = kHeaderBytes + body_size;
    if (total > kMaxPlainBytes || total > result.frame.bytes.size() ||
        total + security::kSecureFrameOverhead > kEspNowPayloadBytes) {
        result.error = Error::TooLarge;
        return result;
    }
    auto* out = result.frame.bytes.data();
    out[0] = kMagic0;
    out[1] = kMagic1;
    out[2] = kVersion;
    out[3] = static_cast<std::uint8_t>(message.type);
    put32(out + 4, message.transfer_id);
    put32(out + 8, message.index);
    put16(out + 12, static_cast<std::uint16_t>(body_size));
    auto* body = out + kHeaderBytes;
    if (message.type == Type::Begin) {
        put32(body, message.image_size);
        put32(body + 4, message.image_crc32);
        std::copy(message.image_sha256.begin(), message.image_sha256.end(), body + 8);
        body[40] = message.board_size;
        std::memcpy(body + 41, message.board.data(), message.board_size);
        const auto version_length_offset = 41 + message.board_size;
        body[version_length_offset] = message.version_size;
        std::memcpy(body + version_length_offset + 1,
                    message.version.data(), message.version_size);
    } else if (message.type == Type::Data) {
        std::copy_n(message.data.begin(), message.data_size, body);
    } else if (message.type == Type::Ack) {
        put32(body, static_cast<std::uint32_t>(message.ack_status));
        put32(body + 4, message.next_index);
        put32(body + 8, message.bytes_written);
    }
    result.frame.size = total;
    return result;
}

DecodeResult decode(const std::uint8_t* bytes, std::size_t size) {
    DecodeResult result;
    if (bytes == nullptr || size < kHeaderBytes) {
        result.error = Error::Truncated;
        return result;
    }
    if (size > kMaxPlainBytes || size > transport::kMaxFrameBytes) {
        result.error = Error::TooLarge;
        return result;
    }
    if (bytes[0] != kMagic0 || bytes[1] != kMagic1) {
        result.error = Error::BadMagic;
        return result;
    }
    if (bytes[2] != kVersion) {
        result.error = Error::BadVersion;
        return result;
    }
    result.message.type = static_cast<Type>(bytes[3]);
    if (!valid_type(result.message.type)) {
        result.error = Error::BadType;
        return result;
    }
    result.message.transfer_id = get32(bytes + 4);
    result.message.index = get32(bytes + 8);
    if (result.message.transfer_id == 0) {
        result.error = Error::InvalidValue;
        return result;
    }
    const std::size_t body_size = get16(bytes + 12);
    if (body_size != size - kHeaderBytes) {
        result.error = Error::LengthMismatch;
        return result;
    }
    const auto* body = bytes + kHeaderBytes;
    switch (result.message.type) {
        case Type::Begin: {
            if (result.message.index != 0 || body_size < kBeginFixedBytes ||
                body_size > kBeginFixedBytes + 2 * kMaxClaimBytes) break;
            result.message.image_size = get32(body);
            result.message.image_crc32 = get32(body + 4);
            std::copy_n(body + 8, result.message.image_sha256.size(),
                        result.message.image_sha256.begin());
            const std::size_t board_size = body[40];
            if (board_size == 0 || board_size > kMaxClaimBytes ||
                41 + board_size + 1 > body_size) break;
            result.message.board_size = static_cast<std::uint8_t>(board_size);
            std::memcpy(result.message.board.data(), body + 41, board_size);
            const std::size_t version_offset = 41 + board_size;
            const std::size_t version_size = body[version_offset];
            if (version_size == 0 || version_size > kMaxClaimBytes ||
                version_offset + 1 + version_size != body_size) break;
            result.message.version_size = static_cast<std::uint8_t>(version_size);
            std::memcpy(result.message.version.data(), body + version_offset + 1,
                        version_size);
            if (result.message.image_size == 0 ||
                !valid_claim(result.message.board.data(), board_size) ||
                !valid_claim(result.message.version.data(), version_size)) break;
            return result;
        }
        case Type::Data:
            if (body_size == 0 || body_size > kMaxChunkBytes) break;
            result.message.data_size = static_cast<std::uint16_t>(body_size);
            std::copy_n(body, body_size, result.message.data.begin());
            return result;
        case Type::End: case Type::Abort:
            if (body_size == 0) return result;
            break;
        case Type::Ack:
            if (body_size != kAckBodyBytes) break;
            if (!parse_status(get32(body), result.message.ack_status)) break;
            result.message.next_index = get32(body + 4);
            result.message.bytes_written = get32(body + 8);
            return result;
    }
    result.error = Error::MalformedBody;
    return result;
}

}  // namespace gs::fota::secure_wire
