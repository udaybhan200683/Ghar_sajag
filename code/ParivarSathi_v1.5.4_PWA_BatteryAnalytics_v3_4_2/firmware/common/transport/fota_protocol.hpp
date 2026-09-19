#pragma once

#include <cstddef>
#include <cstdint>

namespace gs::fota {

inline constexpr std::uint32_t kMagic = 0x4753464FU;
inline constexpr std::uint8_t kProtocolVersion = 1U;
inline constexpr std::size_t kChunkBytes = 200U;
inline constexpr std::uint8_t kAckFrameType = 0x80U;

enum class MessageType : std::uint8_t {
    Begin = 1U,
    Data = 2U,
    End = 3U,
    Abort = 4U,
};

enum class Status : std::int32_t {
    Ready = 0,
    DataOk = 1,
    Complete = 2,
    Duplicate = 3,
    BadPacket = -1,
    BadSession = -2,
    BadSequence = -3,
    BadCrc = -4,
    BadSize = -5,
    OtaBegin = -6,
    OtaWrite = -7,
    OtaEnd = -8,
    SetBoot = -9,
};

struct __attribute__((packed)) Packet {
    std::uint32_t magic;
    std::uint8_t protocol_version;
    std::uint8_t type;
    std::uint16_t reserved0;
    std::uint32_t session_id;
    std::uint32_t sequence;
    std::uint32_t image_size;
    std::uint32_t image_crc32;
    std::uint16_t payload_length;
    std::uint16_t reserved1;
    std::uint32_t payload_crc32;
    std::uint8_t payload[kChunkBytes];
};

struct __attribute__((packed)) Ack {
    std::uint32_t magic;
    std::uint8_t protocol_version;
    std::uint8_t type;
    std::uint16_t reserved;
    std::uint32_t session_id;
    std::uint32_t acknowledged_sequence;
    std::uint32_t next_sequence;
    std::int32_t status;
    std::uint32_t bytes_written;
};

static_assert(sizeof(Packet) == 232U, "FOTA wire packet changed");
static_assert(sizeof(Ack) == 28U, "FOTA ACK wire packet changed");
static_assert(sizeof(Packet) <= 250U, "FOTA packet exceeds ESP-NOW v1 limit");

inline std::uint32_t crc32_update(std::uint32_t crc, const std::uint8_t* data,
                                  std::size_t size) {
    while (size-- != 0U) {
        crc ^= *data++;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 1U) != 0U ? (crc >> 1U) ^ 0xEDB88320U : crc >> 1U;
        }
    }
    return crc;
}

inline std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    return crc32_update(0xFFFFFFFFU, data, size) ^ 0xFFFFFFFFU;
}

}  // namespace gs::fota
