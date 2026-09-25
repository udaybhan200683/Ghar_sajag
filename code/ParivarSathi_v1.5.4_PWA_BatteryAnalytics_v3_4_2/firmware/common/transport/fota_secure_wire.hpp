#pragma once

#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/common/transport/fota_protocol.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::fota::secure_wire {

// Inner plaintext for the existing runtime AEAD envelope. All integers are
// serialized most-significant byte first; no packed C++ object is sent.
constexpr std::size_t kHeaderBytes = 14;
constexpr std::size_t kMaxChunkBytes = 192;
constexpr std::size_t kMaxClaimBytes = 32;
constexpr std::size_t kBeginFixedBytes = 4 + 4 + 32 + 1 + 1;
constexpr std::size_t kAckBodyBytes = 12;
constexpr std::size_t kEspNowPayloadBytes = 250;
constexpr std::size_t kMaxPlainBytes = kEspNowPayloadBytes - security::kSecureFrameOverhead;
static_assert(kHeaderBytes + kMaxChunkBytes + security::kSecureFrameOverhead == 234);
static_assert(kHeaderBytes + kMaxChunkBytes <= kMaxPlainBytes);
static_assert(kMaxPlainBytes <= transport::kMaxFrameBytes);
static_assert(kHeaderBytes + kBeginFixedBytes + 2 * kMaxClaimBytes <= kMaxPlainBytes);

enum class Type : std::uint8_t { Begin = 1, Data = 2, End = 3, Abort = 4, Ack = 0x80 };
enum class Error {
    None, InvalidValue, TooLarge, Truncated, BadMagic, BadVersion,
    BadType, LengthMismatch, MalformedBody
};

struct Message {
    Type type{Type::Begin};
    std::uint32_t transfer_id{0};
    std::uint32_t index{0};
    std::uint32_t image_size{0};
    std::uint32_t image_crc32{0};
    std::array<std::uint8_t, 32> image_sha256{};
    std::array<char, kMaxClaimBytes> board{};
    std::uint8_t board_size{0};
    std::array<char, kMaxClaimBytes> version{};
    std::uint8_t version_size{0};
    std::array<std::uint8_t, kMaxChunkBytes> data{};
    std::uint16_t data_size{0};
    Status ack_status{Status::Ready};
    std::uint32_t next_index{0};
    std::uint32_t bytes_written{0};
};

struct EncodeResult {
    Error error{Error::None};
    transport::EncodedFrame frame{};
    explicit operator bool() const { return error == Error::None; }
};

struct DecodeResult {
    Error error{Error::None};
    Message message{};
    explicit operator bool() const { return error == Error::None; }
};

EncodeResult encode(const Message& message);
DecodeResult decode(const std::uint8_t* bytes, std::size_t size);

}  // namespace gs::fota::secure_wire
